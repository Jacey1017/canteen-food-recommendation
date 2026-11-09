// 给列表项补上展示用字段：好评率百分比
exports.decorate = list => list.map(d => ({
  ...d,
  pct: d.score == null ? '暂无' : Math.round(d.score * 100) + '%',
  bad_text: d.bad_tags && d.bad_tags.length ? '常见差评：' + d.bad_tags.join('、') : '',
}))
