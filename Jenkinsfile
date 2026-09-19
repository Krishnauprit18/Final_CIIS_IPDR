pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
    }

    environment {
        ECR_REGISTRY = '000000000000.dkr.ecr.us-east-1.localhost:4566'
        AWS_ENDPOINT_URL = 'http://localhost:4566'
        AWS_DEFAULT_REGION = 'us-east-1'
        AWS_REGION = 'us-east-1'

        // Dummy Floci credentials only.
        AWS_ACCESS_KEY_ID = 'test'
        AWS_SECRET_ACCESS_KEY = 'test'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm

                script {
                    env.GIT_SHA = sh(
                        script: 'git rev-parse --short=12 HEAD',
                        returnStdout: true
                    ).trim()

                    env.BACKEND_IMAGE = "ciis-backend:${env.GIT_SHA}"
                    env.WEB_IMAGE = "ciis-web:${env.GIT_SHA}"
                }

                sh '''
                    echo "Branch: ${BRANCH_NAME:-unknown}"
                    echo "Commit: ${GIT_SHA}"
                '''
            }
        }

        stage('Tool Versions') {
            steps {
                sh '''
                    git --version
                    python3 --version
                    node --version
                    npm --version
                    docker --version
                    docker compose version
                    aws --version
                    helm version --short
                    terraform version
                '''
            }
        }

        stage('Backend Lint') {
            steps {
                sh 'bash scripts/ci/backend-lint.sh'
            }
        }

        stage('Backend Unit Tests') {
            steps {
                sh 'bash scripts/ci/backend-test.sh'
            }
        }

        stage('Frontend CI') {
            steps {
                sh 'bash scripts/ci/frontend-ci.sh'
            }
        }

        stage('Docker Build') {
            steps {
                sh 'bash scripts/ci/build-images.sh'
            }
        }

        stage('Trivy Image Scan') {
            steps {
                sh 'bash scripts/ci/scan-images.sh'
            }
        }

        stage('Helm Validate') {
            steps {
                sh 'bash scripts/ci/helm-validate.sh'
            }
        }

        stage('Terraform Validate') {
            steps {
                sh 'bash scripts/ci/terraform-validate.sh'
            }
        }

        stage('Container Integration') {
            steps {
                sh '''
                    BACKEND_IMAGE="${BACKEND_IMAGE}" \
                    bash scripts/ci/container-integration.sh
                '''
            }
        }

        stage('Publish Immutable Images') {
            when {
                anyOf {
                    branch 'master'

                    branch pattern: 'release/*',
                           comparator: 'GLOB'
                }
            }

            steps {
                sh 'bash scripts/ci/publish-images.sh'
            }
        }
    }

    post {
        always {
            sh '''
                docker rm -f \
                    ciis-ci-api \
                    ciis-ci-worker \
                    ciis-worker-smoke \
                    ciis-api \
                    ciis-frontend \
                    >/dev/null 2>&1 || true

                docker compose \
                    -f compose.db.yaml \
                    down \
                    >/dev/null 2>&1 || true

                docker compose \
                    -f compose.storage.yaml \
                    down \
                    >/dev/null 2>&1 || true

                docker compose \
                    -f compose.queue.yaml \
                    down \
                    >/dev/null 2>&1 || true
            '''

            archiveArtifacts(
                artifacts: '.ci-artifacts/**',
                allowEmptyArchive: true
            )
        }

        success {
            echo 'CIIS Phase 18 pipeline PASSED.'
        }

        failure {
            echo 'CIIS Phase 18 pipeline FAILED.'
        }
    }
}
