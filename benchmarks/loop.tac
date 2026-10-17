# A loop. Values used inside it have loop_depth 1, so cost x10 to spill.
func sumloop
  t1 = 0
  t2 = 1
label L1
  t3 = t1 + t2
  t1 = t3
  t2 = t2 + 1
  if t2 < 100 goto L1
  ret t1
end
