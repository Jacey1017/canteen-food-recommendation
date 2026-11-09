const { request } = require('../../utils/api')
const { decorate } = require('../../utils/format')

const TAGS_DOWN = ['太咸', '太油', '偏凉', '量少', '不新鲜', '太辣', '贵']
const TAGS_UP = ['好吃', '量足', '性价比高', '热乎', '清淡']

function currentMeal() {
  const h = new Date().getHours()
  if (h < 10) return 'breakfast'
  if (h < 15) return 'lunch'
  if (h < 21) return 'dinner'
  return 'snack'
}

Page({
  data: { dish: null, liked: null, tagOptions: [], picked: {}, text: '' },

  onLoad({ id }) {
    this.id = Number(id)
    request('/dishes/' + id).then(d => this.setData({ dish: decorate([d])[0] }))
  },

  choose(e) {
    const liked = e.currentTarget.dataset.liked === '1'
    this.setData({ liked, tagOptions: liked ? TAGS_UP : TAGS_DOWN, picked: {} })
  },

  toggleTag(e) {
    const t = e.currentTarget.dataset.tag
    const picked = { ...this.data.picked, [t]: !this.data.picked[t] }
    if (Object.keys(picked).filter(k => picked[k]).length > 5) return
    this.setData({ picked })
  },

  onText(e) { this.setData({ text: e.detail.value }) },

  submit() {
    const { liked, picked, text } = this.data
    if (liked === null) return wx.showToast({ title: '先选👍或👎', icon: 'none' })
    request('/reviews', {
      method: 'POST', auth: true,
      data: { dish_id: this.id, liked, tags: Object.keys(picked).filter(k => picked[k]), text, meal: currentMeal() },
    }).then(() => {
      wx.showToast({ title: '谢谢你的评价' })
      setTimeout(() => wx.navigateBack(), 800)
    }).catch(() => wx.showToast({ title: '提交失败', icon: 'none' }))
  },
})
