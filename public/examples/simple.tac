# Simplest possible case: five values, three registers needed.
# a and e never overlap, so they can share a register.
func main
  t1 = 1
  t2 = 2
  t3 = t1 + t2
  t4 = t3
  t5 = t4 * 2
  ret t5
end
