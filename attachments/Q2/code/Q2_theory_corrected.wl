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

(* p(x)=2 x/h^2; n-point midpoint quadrature on [0,h] *)
expectedD[a_?NumericQ, b_?NumericQ] := Module[{xs, w},
  xs = Table[h (k + 0.5)/n, {k, 0, n - 1}];
  w = 2 xs/h^2;
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
