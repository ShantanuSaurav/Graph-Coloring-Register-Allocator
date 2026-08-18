# Adapted from the worked example in Briggs et al. (1994).
# Hand-coloured by the team for K = 3 and K = 4 as a known-correct fixture.
# See docs/briggs_example_solution.md for the expected colouring.
func briggs
  t1 = 1
  t2 = 2
  t3 = t1 + t2
  t4 = t1 + t3
  t5 = t2 + t3
  t6 = t4 + t5
  t7 = t4 + t6
  t8 = t5 + t7
  ret t8
end
