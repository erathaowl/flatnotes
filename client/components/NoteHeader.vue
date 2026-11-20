<template>
  <header class="mb-3 flex flex-col gap-3">
    <div class="min-w-0 w-full">
      <input
        v-if="editing"
        ref="titleInput"
        :value="title"
        placeholder="Title"
        :aria-invalid="titleError"
        aria-label="Note title"
        class="w-full min-w-0 bg-theme-background text-2xl outline-none placeholder:italic placeholder:text-theme-text-very-muted sm:text-3xl"
        @input="onInput"
      />
      <h1 v-else class="break-words text-2xl sm:text-3xl">{{ displayTitle }}</h1>
      <p v-if="titleError" class="mt-1 text-sm text-theme-danger" role="alert">
        Title is required.
      </p>
    </div>
    <slot />
  </header>
</template>

<script setup>
import { ref } from "vue";

defineProps({
  title: { type: String, default: "" },
  displayTitle: { type: String, default: "" },
  editing: { type: Boolean, default: false },
  titleError: { type: Boolean, default: false },
});
const emit = defineEmits(["update:title", "titleInput"]);
const titleInput = ref(null);

function onInput(event) {
  emit("update:title", event.target.value);
  emit("titleInput");
}

defineExpose({ focusTitle: () => titleInput.value?.focus() });
</script>
