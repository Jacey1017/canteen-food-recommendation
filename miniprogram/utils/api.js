// 开发时指向本机后端（需在开发者工具勾选"不校验合法域名"）；上线换成已备案的 https 域名并配置到小程序后台
const BASE = 'http://127.0.0.1:8000'

let tokenPromise = null

function login() {
  const saved = wx.getStorageSync('token')
  if (saved) return Promise.resolve(saved)
  if (!tokenPromise) {
    tokenPromise = new Promise((resolve, reject) => {
      wx.login({
        success: ({ code }) => wx.request({
          url: BASE + '/auth/login', method: 'POST', data: { code },
          success: r => { wx.setStorageSync('token', r.data.token); resolve(r.data.token) },
          fail: reject,
        }),
        fail: reject,
      })
    }).finally(() => { tokenPromise = null })
  }
  return tokenPromise
}

function request(path, { method = 'GET', data, auth = false } = {}, retry = true) {
  return (auth ? login() : Promise.resolve(null)).then(token => new Promise((resolve, reject) => {
    wx.request({
      url: BASE + path, method, data,
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success: r => {
        if (r.statusCode === 401 && retry) { // token 过期：清掉重登一次
          wx.removeStorageSync('token')
          return request(path, { method, data, auth }, false).then(resolve, reject)
        }
        r.statusCode < 400 ? resolve(r.data) : reject(r)
      },
      fail: reject,
    })
  }))
}

module.exports = { request }
