# Diamond control flow: two paths that rejoin. Tests the union in OUT[B].
func diamond
  t1 = 10
  t2 = 20
  if t1 < t2 goto THEN
  t3 = t1 + t1
  goto JOIN
label THEN
  t3 = t2 + t2
label JOIN
  t4 = t3 + t1
  ret t4
end
