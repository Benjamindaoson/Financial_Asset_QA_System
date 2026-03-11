---
category: 金融知识
tags: [金融, 投资]
language: zh
update_date: 2026-03-10
---

# 期权Greeks专题

## Greeks 是什么
Greeks 是衡量期权价格对不同风险因子敏感度的一组指标。它们帮助交易者理解头寸风险，而不是只盯着方向判断。

## Delta
Delta 衡量标的价格变化 1 个单位时，期权价格大约变化多少。

直观理解：
- 看涨期权 Delta 为正
- 看跌期权 Delta 为负
- 越实值，Delta 越接近 1 或 -1

用途：
- 判断方向暴露
- 做 Delta 对冲

## Gamma
Gamma 衡量 Delta 自身变化的速度。

特点：
- 平值、临近到期的期权 Gamma 往往更高
- Gamma 高意味着仓位对标的变动更敏感，风险变化更快

## Theta
Theta 衡量时间流逝对期权价格的影响，也就是常说的“时间价值损耗”。

一般来说：
- 期权买方通常承受负 Theta
- 期权卖方通常获得正 Theta

## Vega
Vega 衡量隐含波动率变化对期权价格的影响。

直观理解：
- 隐含波动率上升，期权通常更贵
- 临近重大事件前，Vega 风险往往更重要

## Rho
Rho 衡量利率变化对期权价格的影响。对长期期权和利率敏感资产更值得关注。

## Greeks 如何联动理解
- Delta 看方向
- Gamma 看方向风险变化速度
- Theta 看时间损耗
- Vega 看波动率风险

真正的期权头寸往往是这几种风险共同作用的结果。

## 常见策略中的 Greeks 特征

### 买入看涨
- 正 Delta
- 正 Gamma
- 负 Theta
- 正 Vega

### 卖出看涨
- 负 Delta
- 负 Gamma
- 正 Theta
- 负 Vega

### 跨式策略
- 方向中性
- 正 Gamma
- 负 Theta
- 正 Vega

## 实务风险提示
- 不能只看 Delta，忽略 Gamma 和 Theta
- 事件前的波动率回落，可能让方向判断正确但仍然亏损
- 临近到期时，Greeks 变化会加快

## 一句话结论
Greeks 的价值在于把“我赌方向”升级成“我知道自己到底暴露在哪些风险上”。
