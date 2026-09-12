# 问题三代码清单

这里保留论文涉及的五代策略和运行所需公共模块。`p3_joint.py` 是最终联合调度策略，
其依赖关系为：`p3_joint` → `p3_adaptive` → `p3_homing`、`p3_frontier`、
`p3_coverage` → `p3_robot`、`p3_arena`、`p3_expect_field`；`p3_bench` 和
`p3_adaptive_bench` 提供离线场景生成器，`p1_intersection` 提供共享几何运算。

`run_p3_paper.py` 是附件内的稳定调用器，转发至 `../research_archive/scripts/`
中的冻结实验驱动程序，以确保结果目录、哈希校验和审计规则保持一致。完整历史
诊断、调参脚本在 `../research_archive/src/`，不属于提交附件。
