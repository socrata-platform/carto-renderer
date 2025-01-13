@Library('socrata-pipeline-library@0.1.0') _

Map pipelineParams = [
  defaultBuildWorker: 'build-worker',
  deploymentEcosystem: 'marathon-mesos',
  language: 'python',
  projectName: 'carto-renderer',
  teamsChannelWebhookId: 'WORKFLOW_IQ',
  testFilePath: 'bin/test.sh',
]

commonServicePipeline(pipelineParams)
