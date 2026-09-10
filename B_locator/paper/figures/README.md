# figures/ —— 图片目录

存放论文插图。命名与格式规范：

1. **命名**：用英文/数字组合，不要用中文、不要用 `1,2,3` 这种顺序命名，
   尽量有意义（如 `flowchart.png`、`locate-area.png`、`trajectory.png`）。
2. **格式**：位图用 `jpg`/`png`（避免 `bmp`）；矢量图用 `pdf`（推荐）/`eps`。
3. **插入示例**（在相应 tex 中）：
   ```latex
   \begin{figure}[!h]
       \centering
       \includegraphics[width=.6\textwidth]{flowchart}
       \caption{总体技术路线图}
       \label{fig:flowchart}
   \end{figure}
   ```
   引用：`\cref{fig:flowchart}`。
4. 当前正文骨架**未引用任何图片**（保证首次编译不报错）；成文时把图片放入本目录，
   再在相应章节补上 `\includegraphics` 即可。
