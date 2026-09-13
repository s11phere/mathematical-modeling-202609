(* Q2 theoretical expected diameter; direct midpoint quadrature *)
ClearAll["Global`*"];
baseDir = If[NotebookDirectory[] === $Failed, Directory[], NotebookDirectory[]];
SetDirectory[baseDir];

h = 1500.;
alpha = Pi/90.;
n = 200;
gridA = Range[-500, 1795, 15];
gridB = Range[-1800, 1800, 15];

(* D(x,a,b) from the theoretical derivation *)
d[x_?NumericQ, a_?NumericQ, b_?NumericQ] :=
  If[Abs[b] < 10^-12, Indeterminate,
    alpha/Abs[b] * Sqrt[(x - a)^2 + b^2] *
      Sqrt[(x + Abs[x - a])^2 + b^2]];

(* 源位先验权函数（有效接收半径 x_max 在 1000~1500 m 之间取均匀分布）：
     0 <= x < 1000                 : w(x) 正比于 x
     1000 <= x <= 1500             : w(x) 正比于 x (1 - (x-1000)/500)
   即面积先验 w 正比于 x 乘上存活因子 P(x_max >= x)。
   归一化常数 3/2375000 在下面的 Total[w] 中约去。
   n-point midpoint quadrature on [0,h] *)
expectedD[a_?NumericQ, b_?NumericQ] := Module[{xs, w},
  xs = Table[h (k + 0.5)/n, {k, 0, n - 1}];
  w = xs (1 - Clip[(xs - 1000.)/(h - 1000.), {0, 1}]);
  Total[w (d[#, a, b] & /@ xs)]/Total[w]
];

data = Flatten[
  Table[{N[a], N[b], expectedD[a, b]}, {b, gridB}, {a, gridA}], 1];
cleanData = Select[data, NumericQ[#[[3]]] &];

outFile = FileNameJoin[{baseDir, "Q2_expected_diameter_data.csv"}];
Export[outFile, Prepend[cleanData, {"a", "b", "d_m"}], "CSV"];

k = First@Ordering[cleanData[[All, 3]], 1];
Print["导出完成：", Length[cleanData], " 行"];
Print["最小值：", cleanData[[k, 3]], " m，位置 (a,b)=",
  cleanData[[k, {1, 2}]]];
Print["文件：", outFile];
