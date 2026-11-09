const { request } = require('../../utils/api')
const { decorate } = require('../../utils/format')

Page({
  data: { list: [], loading: true },

  onShow() { this.load() },
  onPullDownRefresh() { this.load().then(() => wx.stopPullDownRefresh()) },

  load() {
    return request('/rank/avoid?limit=20')
      .then(list => this.setData({ list: decorate(list), loading: false }))
      .catch(() => { this.setData({ loading: false }); wx.showToast({ title: '加载失败', icon: 'none' }) })
  },

  openDish(e) { wx.navigateTo({ url: '/pages/dish/dish?id=' + e.currentTarget.dataset.id }) },
})
