pipeline {
  agent {
    kubernetes {
      yaml """
apiVersion: v1
kind: Pod
metadata:
  labels:
    app: ai-cicd-jenkins-agent
spec:
  serviceAccountName: jenkins
  restartPolicy: Never
  containers:
    - name: node
      image: node:20-bookworm-slim
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "300m"
          memory: "512Mi"
        limits:
          cpu: "1"
          memory: "1Gi"

    - name: kaniko
      image: gcr.io/kaniko-project/executor:debug
      command:
        - /busybox/cat
      tty: true
      resources:
        requests:
          cpu: "500m"
          memory: "1Gi"
        limits:
          cpu: "2"
          memory: "3Gi"

    - name: trivy
      image: public.ecr.aws/aquasecurity/trivy:0.71.0
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "300m"
          memory: "512Mi"
        limits:
          cpu: "1"
          memory: "2Gi"

    - name: kubectl
      image: bitnami/kubectl:latest
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        limits:
          cpu: "500m"
          memory: "512Mi"

    - name: python
      image: python:3.11-slim
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        limits:
          cpu: "500m"
          memory: "512Mi"
"""
      defaultContainer 'node'
    }
  }

  options {
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    IMAGE_NAME = "ai-cicd-nodeapp"
    K8S_NAMESPACE = "ai-cicd"
    OLLAMA_URL = "http://ollama.ai-cicd.svc.cluster.local:11434"
    OLLAMA_MODEL = "llama3.2:1b"
    CURRENT_STAGE = "STARTED"
    IMAGE_FULL_NAME = ""
    GIT_COMMIT_SHORT = ""
  }

  stages {
    stage('Checkout') {
      steps {
        script {
          env.CURRENT_STAGE = "Checkout"
        }
        checkout scm
        sh '''
          mkdir -p logs
          git rev-parse --short HEAD > logs/git-commit.log
          cat logs/git-commit.log
        '''
        script {
          env.GIT_COMMIT_SHORT = sh(script: "cat logs/git-commit.log", returnStdout: true).trim()
        }
      }
    }

    stage('Install Dependencies') {
      steps {
        script {
          env.CURRENT_STAGE = "Install Dependencies"
        }
        container('node') {
          sh '''
            mkdir -p logs
            cd app
            npm ci > ../logs/npm-install.log 2>&1
            status=$?
            cat ../logs/npm-install.log
            exit $status
          '''
        }
      }
    }

    stage('Run Unit Tests') {
      steps {
        script {
          env.CURRENT_STAGE = "Run Unit Tests"
        }
        container('node') {
          sh '''
            cd app
            npm test > ../logs/unit-test.log 2>&1
            status=$?
            cat ../logs/unit-test.log
            exit $status
          '''
        }
      }
    }

    stage('Build and Push Docker Image') {
      steps {
        script {
          env.CURRENT_STAGE = "Build and Push Docker Image"
        }
        container('kaniko') {
          withCredentials([
            usernamePassword(
              credentialsId: 'dockerhub-creds',
              usernameVariable: 'DOCKER_USER',
              passwordVariable: 'DOCKER_PASS'
            )
          ]) {
            sh '''
              mkdir -p logs
              mkdir -p /kaniko/.docker

              cat > /kaniko/.docker/config.json <<CONFIG
{
  "auths": {
    "https://index.docker.io/v1/": {
      "username": "${DOCKER_USER}",
      "password": "${DOCKER_PASS}"
    }
  }
}
CONFIG

              IMAGE="${DOCKER_USER}/${IMAGE_NAME}:${GIT_COMMIT_SHORT}"
              echo "$IMAGE" > logs/image-name.log

              /kaniko/executor \
                --context "${WORKSPACE}" \
                --dockerfile "${WORKSPACE}/Dockerfile" \
                --destination "${IMAGE}" \
                --destination "${DOCKER_USER}/${IMAGE_NAME}:latest" \
                --cache=true \
                > logs/docker-build.log 2>&1

              status=$?
              cat logs/docker-build.log
              exit $status
            '''
          }
        }
        script {
          env.IMAGE_FULL_NAME = sh(script: "cat logs/image-name.log", returnStdout: true).trim()
        }
      }
    }

    stage('Trivy Security Scan') {
      steps {
        script {
          env.CURRENT_STAGE = "Trivy Security Scan"
        }
        container('trivy') {
          sh '''
            mkdir -p logs .trivycache

            trivy image \
              --cache-dir .trivycache \
              --severity HIGH,CRITICAL \
              --ignore-unfixed \
              --exit-code 1 \
              --format table \
              -o logs/trivy-report.txt \
              "${IMAGE_FULL_NAME}"

            status=$?
            cat logs/trivy-report.txt
            exit $status
          '''
        }
      }
    }

    stage('Deploy to Kubernetes') {
      steps {
        script {
          env.CURRENT_STAGE = "Deploy to Kubernetes"
        }
        container('kubectl') {
          sh '''
            mkdir -p logs

            cp k8s/deployment.yaml /tmp/deployment.yaml
            sed -i "s|REPLACE_IMAGE|${IMAGE_FULL_NAME}|g" /tmp/deployment.yaml

            kubectl apply -f /tmp/deployment.yaml > logs/k8s-deploy.log 2>&1
            kubectl apply -f k8s/service.yaml >> logs/k8s-deploy.log 2>&1
            kubectl apply -f k8s/hpa.yaml >> logs/k8s-deploy.log 2>&1

            kubectl rollout status deployment/ai-cicd-nodeapp \
              -n "${K8S_NAMESPACE}" \
              --timeout=180s >> logs/k8s-deploy.log 2>&1

            kubectl get pods,svc,hpa -n "${K8S_NAMESPACE}" >> logs/k8s-deploy.log 2>&1

            status=$?
            cat logs/k8s-deploy.log
            exit $status
          '''
        }
      }
    }
  }

  post {
    success {
      archiveArtifacts artifacts: 'logs/**', fingerprint: true

      container('python') {
        withCredentials([
          string(credentialsId: 'slack-webhook', variable: 'SLACK_WEBHOOK_URL')
        ]) {
          sh '''
            python3 - <<PY
import json
import os
import urllib.request

msg = f"""
✅ *AI CI/CD Pipeline Successful*

*Job:* {os.environ.get('JOB_NAME')}
*Build:* {os.environ.get('BUILD_NUMBER')}
*Image:* {os.environ.get('IMAGE_FULL_NAME')}
*Commit:* {os.environ.get('GIT_COMMIT_SHORT')}
*Build URL:* {os.environ.get('BUILD_URL')}

Deployment completed successfully.
"""

webhook = os.environ.get("SLACK_WEBHOOK_URL")
req = urllib.request.Request(
    webhook,
    data=json.dumps({"text": msg}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)
urllib.request.urlopen(req, timeout=30)
PY
          '''
        }
      }
    }

    failure {
      archiveArtifacts artifacts: 'logs/**', allowEmptyArchive: true, fingerprint: true

      container('python') {
        withCredentials([
          string(credentialsId: 'slack-webhook', variable: 'SLACK_WEBHOOK_URL')
        ]) {
          sh '''
            python3 ai-analyzer/analyze_failure.py \
              --job "${JOB_NAME}" \
              --build "${BUILD_NUMBER}" \
              --stage "${CURRENT_STAGE}" \
              --build-url "${BUILD_URL}" \
              --commit "${GIT_COMMIT_SHORT}" \
              --logs-dir logs \
              --ollama-url "${OLLAMA_URL}" \
              --model "${OLLAMA_MODEL}" \
              --slack-webhook "${SLACK_WEBHOOK_URL}"
          '''
        }
      }

      archiveArtifacts artifacts: 'ai-report/**', allowEmptyArchive: true, fingerprint: true
    }
  }
}
