export function deriveModeFromPresence(presence) {
  const flags = [presence?.leon, presence?.emmi, presence?.elsa]
  const count = flags.filter((value) => value === true).length

  if (count === 3) return 'TRIPLET'
  if (count === 2) return 'PAIR'
  if (count === 1) return 'SINGLE'
  return 'SKIP'
}
