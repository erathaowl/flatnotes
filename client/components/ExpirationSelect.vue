<template>
  <div class="space-y-2">
    <label class="block text-sm font-semibold" :for="selectId">Expiration</label>
    <div class="flex flex-wrap items-center gap-2">
      <select
        :id="selectId"
        v-model="mode"
        class="rounded border border-theme-border bg-theme-background px-3 py-2"
        @change="emitPolicy"
      >
        <option value="none">Never</option>
        <option value="hours">After hours</option>
        <option value="days">After days</option>
        <option value="once">Single view</option>
      </select>
      <input
        v-if="mode === 'hours' || mode === 'days'"
        v-model.number="amount"
        type="number"
        min="1"
        :max="mode === 'hours' ? 87600 : 3650"
        aria-label="Expiration duration"
        class="w-24 rounded border border-theme-border bg-theme-background px-3 py-2"
        @input="emitPolicy"
      />
      <span v-if="mode === 'hours' || mode === 'days'" class="text-sm text-theme-text-muted">
        {{ mode }}
      </span>
    </div>
    <p class="text-xs text-theme-text-muted">
      {{ mode === "once"
        ? "The first authorized opening consumes this note."
        : "Timed expiration starts when the policy is saved. Edits do not reset it." }}
    </p>
  </div>
</template>

<script setup>
import { ref, useId, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "none" },
});
const emit = defineEmits(["update:modelValue"]);
const selectId = useId();
const mode = ref("none");
const amount = ref(1);

watch(() => props.modelValue, (value) => {
  if (value === "none" || value === "once") {
    mode.value = value;
    return;
  }
  const match = /^([1-9]\d*)(h|d)$/.exec(value || "");
  if (match) {
    mode.value = match[2] === "h" ? "hours" : "days";
    amount.value = Number(match[1]);
  }
}, { immediate: true });

function emitPolicy() {
  if (mode.value === "none" || mode.value === "once") {
    emit("update:modelValue", mode.value);
    return;
  }
  const maximum = mode.value === "hours" ? 87600 : 3650;
  const value = Math.min(maximum, Math.max(1, Math.trunc(Number(amount.value) || 1)));
  amount.value = value;
  emit("update:modelValue", value + (mode.value === "hours" ? "h" : "d"));
}
</script>
