pipeline {
  agent {
    kubernetes {
      defaultContainer 'node'
      yaml """
apiVersion: v1
kind: Pod
metadata:
  labels:
    app: ai-cicd-jenkins-agent
spec:
  serviceAccountName: jenkins
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/os: linux
  containers:
    - name: jnlp
      image: jenkins/inbound-agent:latest
      resources:
        requests:
          cpu: "50m"
          memory: "128Mi"
        limits:
          cpu: "300m"
          memory: "512Mi"

    - name: node
      image: node:20-bookworm-slim
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "50m"
          memory: "256Mi"
        limits:
          cpu: "700m"
          memory: "1Gi"

    - name: kaniko
      image: gcr.io/kaniko-project/executor:debug
      command:
        - /busybox/cat
      tty: true
      resources:
        requests:
          cpu: "100m"
          memory: "512Mi"
        limits:
          cpu: "1"
          memory: "2Gi"

    - name: trivy
      image: public.ecr.aws/aquasecurity/trivy:0.71.0
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "50m"
          memory: "384Mi"
        limits:
          cpu: "800m"
          memory: "1536Mi"

    - name: kubectl
      image: bitnami/kubectl:latest
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "25m"
          memory: "128Mi"
        limits:
          cpu: "300m"
          memory: "512Mi"

    - name: python
      image: python:3.11-slim
      command:
        - cat
      tty: true
      resources:
        requests:
          cpu: "25m"
          memory: "128Mi"
        limits:
          cpu: "300m"
          memory: "512Mi"
"""
    }
  }

  options {
    skipDefaultCheckout(true)
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    IMAGE_NAME = "ai-cicd-nodeapp"
    K8S_NAMESPACE = "ai-cicd"
    OLLAMA_URL = "http://ollama.ai-cicd.svc.cluster.local:11434"
    OLLAMA_MODEL = "tinyllama"
    CURRENT_STAGE = "STARTED"
    FAILED_STAGE = "STARTED"
    IMAGE_FULL_NAME = ""
    GIT_COMMIT_SHORT = "unknown"
  }

  stages {
    stage('Checkout') {
      steps {
        script {
          env.CURRENT_STAGE = "Checkout"
          env.FAILED_STAGE = "Checkout"
        }

        container('jnlp') {
          script {
            def scmVars = checkout scm

            if (scmVars.GIT_COMMIT) {
              env.GIT_COMMIT_SHORT = scmVars.GIT_COMMIT.take(7)
            } else {
              env.GIT_COMMIT_SHORT = "unknown"
            }

            sh '''
              mkdir -p logs
            '''

            writeFile file: 'logs/git-commit.log', text: "${env.GIT_COMMIT_SHORT}\n"
            writeFile file: 'logs/current-stage.txt', text: "Checkout\n"

            sh '''
              echo "Checked out commit:"
              cat logs/git-commit.log
            '''
          }
        }
      }
    }

    stage('Install Dependencies') {
      steps {
        script {
          env.CURRENT_STAGE = "Install Dependencies"
          env.FAILED_STAGE = "Install Dependencies"
          writeFile file: 'logs/current-stage.txt', text: "Install Dependencies\n"
        }

        container('node') {
          sh '''
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
          env.FAILED_STAGE = "Run Unit Tests"
          writeFile file: 'logs/current-stage.txt', text: "Run Unit Tests\n"
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
          env.FAILED_STAGE = "Build and Push Docker Image"
          writeFile file: 'logs/current-stage.txt', text: "Build and Push Docker Image\n"
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
              echo "${IMAGE}" > logs/image-name.log

              echo "Building and pushing image: ${IMAGE}"

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
          env.IMAGE_FULL_NAME = readFile('logs/image-name.log').trim()
          echo "Image created: ${env.IMAGE_FULL_NAME}"
        }
      }
    }

    stage('Trivy Security Scan') {
      steps {
        script {
          env.CURRENT_STAGE = "Trivy Security Scan"
          env.FAILED_STAGE = "Trivy Security Scan"
          writeFile file: 'logs/current-stage.txt', text: "Trivy Security Scan\n"
        }

        container('trivy') {
          withCredentials([
            usernamePassword(
              credentialsId: 'dockerhub-creds',
              usernameVariable: 'TRIVY_USERNAME',
              passwordVariable: 'TRIVY_PASSWORD'
            )
          ]) {
            sh '''
              mkdir -p logs .trivycache

              echo "Scanning image: ${IMAGE_FULL_NAME}"

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
    }

    stage('Deploy to Kubernetes') {
      steps {
        script {
          env.CURRENT_STAGE = "Deploy to Kubernetes"
          env.FAILED_STAGE = "Deploy to Kubernetes"
          writeFile file: 'logs/current-stage.txt', text: "Deploy to Kubernetes\n"
        }

        container('kubectl') {
          sh '''
            mkdir -p logs

            echo "Deploying image: ${IMAGE_FULL_NAME}"

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
print("Slack success notification sent.")
PY
          '''
        }
      }
    }

    failure {
      archiveArtifacts artifacts: 'logs/**', allowEmptyArchive: true, fingerprint: true

      script {
        if (fileExists('logs/current-stage.txt')) {
          env.FAILED_STAGE = readFile('logs/current-stage.txt').trim()
        } else {
          env.FAILED_STAGE = env.CURRENT_STAGE
        }

        if (!env.GIT_COMMIT_SHORT || env.GIT_COMMIT_SHORT == "") {
          env.GIT_COMMIT_SHORT = "unknown"
        }

        echo "Detected failed stage: ${env.FAILED_STAGE}"
      }

      container('python') {
        withCredentials([
          string(credentialsId: 'slack-webhook', variable: 'SLACK_WEBHOOK_URL')
        ]) {
          sh '''
            if [ -f ai-analyzer/analyze_failure.py ]; then
              python3 ai-analyzer/analyze_failure.py \
                --job "${JOB_NAME}" \
                --build "${BUILD_NUMBER}" \
                --stage "${FAILED_STAGE}" \
                --build-url "${BUILD_URL}" \
                --commit "${GIT_COMMIT_SHORT}" \
                --logs-dir logs \
                --ollama-url "${OLLAMA_URL}" \
                --model "${OLLAMA_MODEL}" \
                --slack-webhook "${SLACK_WEBHOOK_URL}"
            else
              python3 - <<PY
import json
import os
import urllib.request

msg = f"""
🚨 *CI/CD Pipeline Failed*

*Job:* {os.environ.get('JOB_NAME')}
*Build:* {os.environ.get('BUILD_NUMBER')}
*Failed Stage:* {os.environ.get('FAILED_STAGE')}
*Commit:* {os.environ.get('GIT_COMMIT_SHORT')}
*Build URL:* {os.environ.get('BUILD_URL')}

AI analyzer script was not found in the workspace. Check whether repository checkout completed successfully.
"""

webhook = os.environ.get("SLACK_WEBHOOK_URL")

req = urllib.request.Request(
    webhook,
    data=json.dumps({"text": msg}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

urllib.request.urlopen(req, timeout=30)
print("Fallback Slack failure notification sent.")
PY
            fi
          '''
        }
      }

      archiveArtifacts artifacts: 'ai-report/**', allowEmptyArchive: true, fingerprint: true
    }

    always {
      echo "Pipeline finished. Final status: ${currentBuild.currentResult}"
    }
  }
}
