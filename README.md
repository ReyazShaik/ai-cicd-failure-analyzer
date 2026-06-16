# AI-Powered CI/CD Failure Analysis Pipeline

This project demonstrates a production-grade CI/CD pipeline using:

- GitHub
- Jenkins
- Kubernetes
- Dockerfile-based image builds using Kaniko
- Trivy security scanning
- Ollama local AI failure analysis
- Slack notifications
- Grafana/Prometheus monitoring

## Flow

GitHub → Jenkins → Test → Build Image → Trivy Scan → Kubernetes Deploy → Slack

If any step fails:

Logs → Ollama → AI RCA → Slack
