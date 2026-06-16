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

    GIT_COMMIT_SHORT = "unknown"
    IMAGE_FULL_NAME = ""
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
            checkout scm

            sh '''
              mkdir -p logs
              printf "Checkout\\n" > logs/current-stage.txt
            '''

            env.GIT_COMMIT_SHORT = sh(
              script: '''
                git rev-parse --short HEAD 2>/dev/null || echo unknown
              ''',
              returnStdout: true
            ).trim()

            if (!env.GIT_COMMIT_SHORT || env.GIT_COMMIT_SHORT == "unknown") {
              env.GIT_COMMIT_SHORT = "${BUILD_NUMBER}"
            }

            writeFile file: 'logs/git-commit.log', text: "${env.GIT_COMMIT_SHORT}\n"

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
        }

        container('jnlp') {
          sh '''
            mkdir -p logs
            printf "Install Dependencies\\n" > logs/current-stage.txt
          '''
        }

        container('node') {
          sh '''
            set +e

            cd app

            if [ ! -f package-lock.json ]; then
              echo "ERROR: package-lock.json is missing." > ../logs/npm-install.log
              echo "npm ci requires package-lock.json." >> ../logs/npm-install.log
              echo "Fix: run npm install locally, commit app/package-lock.json, then rerun Jenkins." >> ../logs/npm-install.log
              cat ../logs/npm-install.log
              exit 1
            fi

            npm ci > ../logs/npm-install.log 2>&1
            status=$?

            echo "========== npm install logs =========="
            cat ../logs/npm-install.log
            echo "======================================"

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
        }

        container('jnlp') {
          sh '''
            mkdir -p logs
            printf "Run Unit Tests\\n" > logs/current-stage.txt
          '''
        }

        container('node') {
          sh '''
            set +e

            cd app

            npm test > ../logs/unit-test.log 2>&1
            status=$?

            echo "========== unit test logs =========="
            cat ../logs/unit-test.log
            echo "===================================="

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
        }

        container('jnlp') {
          sh '''
            mkdir -p logs
            printf "Build and Push Docker Image\\n" > logs/current-stage.txt
          '''
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
              set +e

              mkdir -p logs
              mkdir -p /kaniko/.docker

              if [ -z "${DOCKER_USER}" ]; then
                echo "ERROR: DOCKER_USER is empty. Check Jenkins credential ID: dockerhub-creds" | tee logs/docker-build.log
                exit 1
              fi

              COMMIT_TAG="$(cat logs/git-commit.log 2>/dev/null | tr -d '\\r\\n ')"

              if [ -z "${COMMIT_TAG}" ] || [ "${COMMIT_TAG}" = "unknown" ]; then
                COMMIT_TAG="${BUILD_NUMBER}"
              fi

              IMAGE="${DOCKER_USER}/${IMAGE_NAME}:${COMMIT_TAG}"

              echo "${IMAGE}" > logs/image-name.log

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

              echo "Image name saved to logs/image-name.log:"
              cat logs/image-name.log

              echo "Building and pushing image: ${IMAGE}"

              /kaniko/executor \
                --context "${WORKSPACE}" \
                --dockerfile "${WORKSPACE}/Dockerfile" \
                --destination "${IMAGE}" \
                --destination "${DOCKER_USER}/${IMAGE_NAME}:latest" \
                --cache=true \
                > logs/docker-build.log 2>&1

              status=$?

              echo "========== Docker build logs =========="
              cat logs/docker-build.log
              echo "======================================="

              echo "Final image name:"
              cat logs/image-name.log

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
        }

        container('jnlp') {
          sh '''
            mkdir -p logs
            printf "Trivy Security Scan\\n" > logs/current-stage.txt
          '''
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
              set +e

              mkdir -p logs .trivycache

              IMAGE_TO_SCAN="$(cat logs/image-name.log 2>/dev/null | tr -d '\\r\\n ')"

              if [ -z "${IMAGE_TO_SCAN}" ]; then
                echo "ERROR: IMAGE_TO_SCAN is empty." | tee logs/trivy-report.txt
                echo "logs/image-name.log was not created or is empty." | tee -a logs/trivy-report.txt
                echo "Check Build and Push Docker Image stage." | tee -a logs/trivy-report.txt
                exit 1
              fi

              echo "Scanning image: ${IMAGE_TO_SCAN}"

              trivy image \
                --skip-version-check \
                --cache-dir .trivycache \
                --severity HIGH,CRITICAL \
                --ignore-unfixed \
                --exit-code 1 \
                --format table \
                -o logs/trivy-report.txt \
                "${IMAGE_TO_SCAN}"

              status=$?

              echo "========== Trivy scan logs =========="
              cat logs/trivy-report.txt
              echo "====================================="

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
        }

        container('jnlp') {
          sh '''
            mkdir -p logs
            printf "Deploy to Kubernetes\\n" > logs/current-stage.txt
          '''
        }

        container('kubectl') {
          sh '''
            set +e

            mkdir -p logs

            IMAGE_TO_DEPLOY="$(cat logs/image-name.log 2>/dev/null | tr -d '\\r\\n ')"

            if [ -z "${IMAGE_TO_DEPLOY}" ]; then
              echo "ERROR: IMAGE_TO_DEPLOY is empty." | tee logs/k8s-deploy.log
              echo "logs/image-name.log was not created or is empty." | tee -a logs/k8s-deploy.log
              exit 1
            fi

            echo "Deploying image: ${IMAGE_TO_DEPLOY}"

            cp k8s/deployment.yaml /tmp/deployment.yaml
            sed -i "s|REPLACE_IMAGE|${IMAGE_TO_DEPLOY}|g" /tmp/deployment.yaml

            kubectl apply -f /tmp/deployment.yaml > logs/k8s-deploy.log 2>&1
            kubectl apply -f k8s/service.yaml >> logs/k8s-deploy.log 2>&1
            kubectl apply -f k8s/hpa.yaml >> logs/k8s-deploy.log 2>&1

            kubectl rollout status deployment/ai-cicd-nodeapp \
              -n "${K8S_NAMESPACE}" \
              --timeout=180s >> logs/k8s-deploy.log 2>&1

            kubectl get pods,svc,hpa -n "${K8S_NAMESPACE}" >> logs/k8s-deploy.log 2>&1

            status=$?

            echo "========== Kubernetes deploy logs =========="
            cat logs/k8s-deploy.log
            echo "============================================"

            exit $status
          '''
        }
      }
    }
  }

  post {
    success {
      archiveArtifacts artifacts: 'logs/**', fingerprint: true

      script {
        if (fileExists('logs/image-name.log')) {
          env.IMAGE_FULL_NAME = readFile('logs/image-name.log').trim()
        }
        if (fileExists('logs/git-commit.log')) {
          env.GIT_COMMIT_SHORT = readFile('logs/git-commit.log').trim()
        }
      }

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
          def stageFromFile = readFile('logs/current-stage.txt').trim()

          if (stageFromFile && stageFromFile != "STARTED") {
            env.FAILED_STAGE = stageFromFile
          } else {
            env.FAILED_STAGE = env.CURRENT_STAGE
          }
        } else {
          env.FAILED_STAGE = env.CURRENT_STAGE
        }

        if (!env.FAILED_STAGE || env.FAILED_STAGE == "STARTED") {
          env.FAILED_STAGE = "Unknown Failed Stage"
        }

        if (fileExists('logs/git-commit.log')) {
          env.GIT_COMMIT_SHORT = readFile('logs/git-commit.log').trim()
        }

        if (!env.GIT_COMMIT_SHORT || env.GIT_COMMIT_SHORT == "") {
          env.GIT_COMMIT_SHORT = "unknown"
        }

        if (fileExists('logs/image-name.log')) {
          env.IMAGE_FULL_NAME = readFile('logs/image-name.log').trim()
        }

        echo "Detected failed stage: ${env.FAILED_STAGE}"
        echo "Detected commit: ${env.GIT_COMMIT_SHORT}"
        echo "Detected image: ${env.IMAGE_FULL_NAME}"
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
*Image:* {os.environ.get('IMAGE_FULL_NAME')}
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
