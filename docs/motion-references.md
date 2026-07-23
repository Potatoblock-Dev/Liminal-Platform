# 动作系统参考

当前动作系统仍是项目内的轻量实现，没有引入第三方运行时依赖或复制第三方代码。
以下开源项目用于确认程序化动作的常见结构和算法方向：

- [Re50N4NC3/proceduralAnimation2D](https://github.com/Re50N4NC3/proceduralAnimation2D)
  - 两段腿 IK、交替脚步目标、摆动阶段抬脚、身体高度补偿。
- [goldst/IK.ts](https://github.com/goldst/IK.ts)
  - 浏览器端骨骼链与 IK 的组织方式；本项目角色只有两段腿，因此使用更小的解析式解算，
    没有引入迭代式 FABRIK 运行时。
- [ozz-animation Foot IK sample](https://guillaumeblanc.github.io/ozz-animation/samples/foot_ik/)
  - 脚部落点、两段骨骼 IK、骨盆高度修正以及 IK 与基础动作混合的处理顺序。

## 当前采用的原则

1. 先计算脚部目标，再用解析式 two-bone IK 得到髋与膝角度。
2. 目标姿态与实际关节之间继续使用弹簧，避免状态切换时突变。
3. 步态只负责较大的动作趋势，落地压缩、身体倾斜和呼吸保持为独立次级运动。
4. 跪地和腾空姿态与走路姿态做连续混合，不直接覆盖渲染节点。

当前舞台是水平地面，因此尚未加入射线检测与斜坡脚掌对齐；以后增加复杂地形时，
可在现有脚部目标层前增加地面采样，不需要改 UV 或皮套格式。
