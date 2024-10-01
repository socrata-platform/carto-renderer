@Library('socrata-pipeline-library')

String service = 'carto-renderer'
boolean isPr = env.CHANGE_ID != null
String lastStage

def dockerize = new com.socrata.Dockerize(steps, service, BUILD_NUMBER)
def semVerTag = new com.socrata.SemVerTag(steps)

pipeline {
  options {
    ansiColor('xterm')
    disableConcurrentBuilds(abortPrevious: true)
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 20, unit: 'MINUTES')
  }
  parameters {
    string(name: 'AGENT', defaultValue: 'build-worker', description: 'Which build agent to use')
    string(name: 'BRANCH_SPECIFIER', defaultValue: 'origin/main', description: 'Use this branch for building the artifact.')
    booleanParam(name: 'RELEASE_BUILD', defaultValue: false, description: 'Are we building a release candidate?')
  }
  agent {
    label params.AGENT
  }
  environment {
    WEBHOOK_ID = 'WORKFLOW_IQ'
  }
  stages {
    stage('Checkout Release Tag') {
      when {
        expression { return params.RELEASE_BUILD }
      }
      steps {
        script {
          lastStage = env.STAGE_NAME
          semVerTag.checkoutClosestTag()
        }
      }
    }
    stage('Test') {
      steps {
        script {
          lastStage = env.STAGE_NAME
          sh "bin/test.sh"
        }
      }
    }
    stage('Docker Build') {
      steps {
        script {
          lastStage = env.STAGE_NAME
          env.VERSION = sh(returnStdout: true, script: "PYTHONPATH=. python -c 'from carto_renderer.version import SEMANTIC; print(SEMANTIC)'").trim()
          env.DOCKER_TAG = dockerize.dockerBuildWithDefaultTag(
            version: env.VERSION,
            sha: env.GIT_COMMIT
          )
        }
      }
    }
    stage('Publish') {
      when {
        not { expression { isPr } }
      }
      steps {
        script {
          lastStage = env.STAGE_NAME
          if (params.RELEASE_BUILD) {
            env.BUILD_ID = dockerize.publish(sourceTag: env.DOCKER_TAG)
          } else {
            env.BUILD_ID = dockerize.publish(
              sourceTag: env.DOCKER_TAG,
              environments: ['internal']
            )
          }
          currentBuild.description = env.BUILD_ID
        }
      }
    }
    stage('Deploy') {
      when {
        not { expression { isPr } }
      }
      steps {
        script {
          lastStage = env.STAGE_NAME
          String environment = (params.RELEASE_BUILD) ? 'rc' : 'staging'
          marathonDeploy(
            serviceName: service,
            tag: env.BUILD_ID,
            environment: environment
          )
        }
      }
    }
  }
  post {
    failure {
      script {
        boolean buildingMain = env.JOB_NAME == "${service}/main"
        if (buildingMain || params.RELEASE_BUILD) {
          teamsWorkflowMessage(
            message: "[${currentBuild.fullDisplayName}](${env.BUILD_URL}) has failed in stage ${lastStage}",
            workflowCredentialID: WEBHOOK_ID
          )
        }
      }
    }
  }
}
