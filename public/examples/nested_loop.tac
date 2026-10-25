# Nested loops: the inner body sits at loop_depth 2, so cost x100.
func nested
  t1 = 0
  t2 = 0
label OUTER
  t3 = 0
label INNER
  t4 = t1 + t3
  t1 = t4
  t3 = t3 + 1
  if t3 < 10 goto INNER
  t2 = t2 + 1
  if t2 < 10 goto OUTER
  ret t1
end
