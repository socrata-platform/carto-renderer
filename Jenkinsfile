@Library('socrata-pipeline-library@9.0.0') _

commonPipeline(
    jobName: 'carto-renderer',
    language: 'python',
    paths: [
        testExecutable: 'bin/test.sh',
    ],
    projects: [
        [
            name: 'carto-renderer',
            deploymentEcosystem: 'marathon-mesos',
            paths: [
                dockerBuildContext: '.',
            ],
            type: 'service',
        ]
    ],
    teamsChannelWebhookId: 'WORKFLOW_EGRESS_AUTOMATION',
)
