const { request } = require('../../utils/api')
const { decorate } = require('../../utils/format')

Page({
  data: { top: [], fresh: [], loading: true },

  onShow() { this.load() },
  onPullDownRefresh() { this.load().then(() => wx.stopPullDownRefresh()) },

  load() {
    return Promise.all([request('/rank/top?limit=10'), request('/dishes/new?days=7')])
      .then(([top, fresh]) => {
        // 冷启动期还没有足够评价：退回展示全部菜品，保证页面不是空的
        const topList = top.length ? Promise.resolve(top) : request('/dishes?limit=20')
        return topList.then(list => this.setData({ top: decorate(list), fresh: decorate(fresh), loading: false }))
      })
      .catch(() => { this.setData({ loading: false }); wx.showToast({ title: '加载失败', icon: 'none' }) })
  },

  openDish(e) { wx.navigateTo({ url: '/pages/dish/dish?id=' + e.currentTarget.dataset.id }) },
})
