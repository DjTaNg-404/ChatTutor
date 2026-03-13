# 知识图谱查看器

ChatTutor 知识图谱查看器 - 用于可视化和浏览 ChatTutor 生成的知识图谱

## 文件结构

```
kg_viewer/
├── __init__.py          # 包导出
├── app.py               # 主程序入口
├── config.py            # 配置常量（颜色、样式、CSS）
├── data_loader.py       # 数据加载工具
├── graph_renderer.py    # 图谱布局计算和 Plotly 渲染
├── stats_utils.py       # 统计工具和过滤函数
├── sidebar.py           # 侧边栏组件
├── main_view.py         # 主视图组件
└── static/              # 静态资源
    └── think.png        # 思考图标
```

## 运行方式

### 从项目根目录运行（推荐）
```bash
cd Design_Web_Dashboard
streamlit run kg_viewer/app.py
```

**注意**: 必须在 `Design_Web_Dashboard` 目录下运行，这样 Python 才能正确导入 `kg_viewer` 模块中的文件。

## 功能

- **知识图谱可视化**: 使用 Plotly 渲染交互式图谱
- **置信度过滤**: 根据实体置信度阈值过滤节点
- **关系强度过滤**: 根据关系强度过滤边
- **隐藏孤立节点**: 可选隐藏没有连接的节点
- **实体类型图例**: 显示不同实体类型的颜色映射
- **关系类型图例**: 显示不同关系类型的样式
- **统计信息**: 节点数、边数、平均置信度等
- **数据表格**: 查看原始节点和边数据

## 依赖

- streamlit
- plotly
- networkx
- numpy
- pandas
