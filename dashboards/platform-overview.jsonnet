// Compile: jsonnet -J dashboards dashboards/platform-overview.jsonnet
local g = import 'lib/grafana.libsonnet';

g.dashboard('Kate — Platform Overview', uid='kate-platform', refresh='30s') + {
  templating: { list: [g.dsTmpl] },
  panels: [
    g.timeseries(
      title='Requests / sec',
      targets=[
        g.target(
          'sum by (job) (rate(http_requests_total{namespace="platform"}[2m]))',
          '{{job}}',
        ),
      ],
      x=0, y=0, w=24, h=8, unit='reqps',
    ) + { id: 1 },

    g.timeseries(
      title='5xx Error Rate',
      targets=[
        g.target(
          |||
            sum by (job) (rate(http_requests_total{namespace="platform",status_code=~"5.."}[2m]))
            /
            sum by (job) (rate(http_requests_total{namespace="platform"}[2m]))
          |||,
          '{{job}}',
        ),
      ],
      x=0, y=8, w=12, h=8, unit='percentunit',
    ) + { id: 2 },

    g.timeseries(
      title='P99 / P50 Latency',
      targets=[
        g.target(
          'histogram_quantile(0.99, sum by (job, le) (rate(http_request_duration_seconds_bucket{namespace="platform"}[2m])))',
          'p99 {{job}}',
        ),
        g.target(
          'histogram_quantile(0.50, sum by (job, le) (rate(http_request_duration_seconds_bucket{namespace="platform"}[2m])))',
          'p50 {{job}}',
          refId='B',
        ),
      ],
      x=12, y=8, w=12, h=8, unit='s',
    ) + { id: 3 },

    g.timeseries(
      title='Pod Count by Deployment',
      targets=[
        g.target(
          'kube_deployment_status_replicas_available{namespace="platform"}',
          '{{deployment}}',
        ),
      ],
      x=0, y=16, w=12, h=8,
    ) + { id: 4 },

    g.timeseries(
      title='CPU Usage by Pod',
      targets=[
        g.target(
          'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="platform",container!="",container!="POD"}[2m]))',
          '{{pod}}',
        ),
      ],
      x=12, y=16, w=12, h=8, unit='cores',
    ) + { id: 5 },
  ],
}
