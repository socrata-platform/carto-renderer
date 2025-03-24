@Library('socrata-pipeline-library@3.0.0') _

Map pipelineParams = [
    defaultBuildWorker: 'build-worker',
    jobName: 'carto-renderer',
    language: 'python',
    paths: [
        testExecutable: 'bin/test.sh',
    ],
    projects: [
        [
            name: 'carto-renderer',
            deploymentEcosystem: 'marathon-mesos',
            type: 'service',
        ]
    ],
    teamsChannelWebhookId: 'WORKFLOW_IQ',
]

commonPipeline(pipelineParams)
