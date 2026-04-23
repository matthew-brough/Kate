// Minimal Grafana dashboard helpers — no external deps.
{
  local g = self,

  dashboard(title, uid, refresh='30s'):: {
    title: title,
    uid: uid,
    schemaVersion: 38,
    version: 1,
    refresh: refresh,
    time: { from: 'now-1h', to: 'now' },
    timezone: 'browser',
    tags: ['kate'],
    panels: [],
    templating: { list: [] },
  },

  dsTmpl:: {
    name: 'datasource',
    type: 'datasource',
    pluginId: 'prometheus',
    query: 'prometheus',
    current: {},
    hide: 0,
    includeAll: false,
    label: 'Data Source',
  },

  timeseries(title, targets, x, y, w=12, h=8, unit='short'):: {
    id: std.length(targets),  // rough unique id; override if needed
    type: 'timeseries',
    title: title,
    gridPos: { x: x, y: y, w: w, h: h },
    datasource: { type: 'prometheus', uid: '${datasource}' },
    fieldConfig: {
      defaults: {
        unit: unit,
        custom: { lineWidth: 2, fillOpacity: 10 },
      },
      overrides: [],
    },
    options: {
      tooltip: { mode: 'multi', sort: 'desc' },
      legend: { displayMode: 'list', placement: 'bottom' },
    },
    targets: targets,
  },

  target(expr, legendFormat, refId='A'):: {
    datasource: { type: 'prometheus', uid: '${datasource}' },
    expr: expr,
    legendFormat: legendFormat,
    refId: refId,
  },
}
