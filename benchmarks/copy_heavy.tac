# Copy-heavy benchmark, purpose-built to exercise coalescing under real register
# pressure (not a trivial "two temps, one copy" toy).
#
# t1..t4 are four independent base values. Each is copied once (t5=t1, t6=t2, t7=t3,
# t8=t4) and BOTH the original and the copy are used later (t9..t11 consume the
# copies, t12..t13 consume the originals again), so all eight stay live at the same
# time around t9. Because build_graph() deliberately does not add an edge between a
# copy's destination and its own source, t1-t5, t2-t6, t3-t7 and t4-t8 are each safe
# to merge, but every OTHER pair among {t1..t8} does interfere (they are all live
# together at t9) -- an 8-node cluster that is one edge short of complete, missing
# exactly its four copy pairs. That is the textbook shape coalescing is meant for:
# merging each copy pair collapses the cluster from 8 live ranges to 4, which is the
# difference between needing 4 registers and needing up to 7.
#
# A second, smaller copy chain (t16->t17->t18) at the end exercises multi-hop
# coalescing (chained copies, not just single pairs).
func copy_heavy
  t1 = 1
  t2 = 2
  t3 = 3
  t4 = 4
  t5 = t1
  t6 = t2
  t7 = t3
  t8 = t4
  t9 = t5 + t6
  t10 = t7 + t8
  t11 = t9 + t10
  t12 = t1 + t2
  t13 = t3 + t4
  t14 = t11 + t12
  t15 = t14 + t13
  t16 = t15
  t17 = t16
  t18 = t17
  ret t18
end
