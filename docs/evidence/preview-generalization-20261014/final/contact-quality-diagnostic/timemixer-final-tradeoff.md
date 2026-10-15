# TimeMixer final geometry tradeoff (v14 to v18)

Actual `single-0-depth-3` captures from frozen v14 and formal v18 retain identical node geometry and identical recursive source authority. The two changed edges keep their full bindings, independent value slots, physical port records and named gates. All final source, geometry, label, routing, junction and restoration checks pass.

Only two painted routes change. `route-0213-212` (`season.step0 → season.list:scale[1]`) removes a 28px detour and four bends, putting its main vertical lane at x917. `route-0214-213` (`season.step1 → season.list:scale[2]`) moves its free lane from x921 to x927, retains its exact endpoint at x931/y1515.24 and uses a 2px terminal-adjacent band at y1517.24. It adds two bends without increasing length. Net length −28 and bends −2. The 14px band of rejected v16/v17 intermediate geometry does not survive in the final route.

Two old T touches at x931 (y1715.74 and y1605.03, pairs 0201/0213 and 0202/0213) become crossings at x917. Their routes remain independent and visibly separated; these are conversions on the same pairs, not new independent contact pairs. The old crossing and old T touch between 0213/0214 both disappear. Two other crossings against 0214 move from x921 to x927. Thus strict crossings increase 11→12, all contacts decrease 14→12, and touches decrease 3→0. There is no new contact pair.

Near-parallel runs remain three, close-run length remains exactly 697px and minimum gap remains 1px, matching v14; the terminal band is 2px. The same measured tradeoff occurs in the other two depth-3 matrix stages. Depth-2 and fully open final frontiers improve close-run length further; all 24 mixed stages pass.

Full actual routes, node/authority equality, contact coordinates, near-parallel segment pairs, runtime and capture hashes are in `timemixer-v14-v18-route-diff.json`. This retains the explicit strict-crossing tradeoff while resolving ambiguous T contacts and avoiding additional crowding.
