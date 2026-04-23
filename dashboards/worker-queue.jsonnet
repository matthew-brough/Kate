// Compile: jsonnet -J dashboards dashboards/worker-queue.jsonnet
local g = import 'lib/grafana.libsonnet';

g.dashboard('Kate — Worker & Queue', uid='kate-worker', refresh='15s') + {
  templating: { list: [g.dsTmpl] },
  panels: [
    g.timeseries(
      title='Celery Queue Depth',
      targets=[
        g.target('redis_list_length{key="celery"}', 'queue depth'),
      ],
      x=0, y=0, w=12, h=8,
    ) + { id: 1 },

    g.timeseries(
      title='Worker Replicas',
      targets=[
        g.target(
          'kube_deployment_status_replicas{namespace="platform",deployment="worker"}',
          'total',
        ),
        g.target(
          'kube_deployment_status_replicas_available{namespace="platform",deployment="worker"}',
          'available',
          refId='B',
        ),
      ],
      x=12, y=0, w=12, h=8,
    ) + { id: 2 },

    g.timeseries(
      title='Report Request Rate',
      targets=[
        g.target(
          'sum(rate(http_requests_total{namespace="platform",job="report-api",handler=~"/reports.*",method="POST"}[2m]))',
          'POST /reports',
        ),
      ],
      x=0, y=8, w=12, h=8, unit='reqps',
    ) + { id: 3 },

    g.timeseries(
      title='Memory Usage by Pod',
      targets=[
        g.target(
          'sum by (pod) (container_memory_working_set_bytes{namespace="platform",container!="",container!="POD"})',
          '{{pod}}',
        ),
      ],
      x=12, y=8, w=12, h=8, unit='bytes',
    ) + { id: 4 },
  ],
}
