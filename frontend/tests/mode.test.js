import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive, computed } from 'vue'
import { deriveModeFromPresence } from '../src/mode.js'

test('deriveModeFromPresence returns the expected modes', () => {
  assert.equal(deriveModeFromPresence({ leon: true, emmi: true, elsa: true }), 'TRIPLET')
  assert.equal(deriveModeFromPresence({ leon: true, emmi: true, elsa: false }), 'PAIR')
  assert.equal(deriveModeFromPresence({ leon: true, emmi: false, elsa: false }), 'SINGLE')
  assert.equal(deriveModeFromPresence({ leon: false, emmi: false, elsa: false }), 'SKIP')
})

test('deriveModeFromPresence degrades gracefully on unexpected values', () => {
  assert.equal(deriveModeFromPresence({ leon: null, emmi: undefined, elsa: -1 }), 'SKIP')
  assert.equal(deriveModeFromPresence({ leon: true, emmi: 1, elsa: false }), 'SINGLE')
})

test('computed preview updates immediately when presence changes', async () => {
  const presence = reactive({
    leon: true,
    emmi: true,
    elsa: true,
  })
  const preview = computed(() => deriveModeFromPresence(presence))

  assert.equal(preview.value, 'TRIPLET')

  presence.elsa = false
  await nextTick()
  assert.equal(preview.value, 'PAIR')

  presence.emmi = false
  await nextTick()
  assert.equal(preview.value, 'SINGLE')

  presence.leon = false
  await nextTick()
  assert.equal(preview.value, 'SKIP')

  presence.leon = true
  await nextTick()
  assert.equal(preview.value, 'SINGLE')
})
