# Eight values all live at once. Colourable with K=8, forces a spill at K=4.
func pressure
  t1 = 1
  t2 = 2
  t3 = 3
  t4 = 4
  t5 = 5
  t6 = 6
  t7 = 7
  t8 = 8
  t9 = t1 + t2
  t10 = t9 + t3
  t11 = t10 + t4
  t12 = t11 + t5
  t13 = t12 + t6
  t14 = t13 + t7
  t15 = t14 + t8
  ret t15
end
