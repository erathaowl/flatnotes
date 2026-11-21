<template>
  <!-- Mask -->
  <div
    v-if="isVisible"
    class="fixed inset-0 z-50 flex h-dvh w-dvw items-center justify-center bg-slate-950/40 px-2 py-4 backdrop-blur-sm"
    @click.self="closeHandler"
  >
    <!-- Modal -->
    <div
      role="dialog"
      aria-modal="true"
      class="relative max-h-full min-h-0 w-full max-w-[500px] overflow-y-auto overscroll-contain rounded-lg border border-theme-border bg-theme-background shadow-lg [-webkit-overflow-scrolling:touch]"
      :class="$attrs.class"
    >
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import Mousetrap from "mousetrap";

defineOptions({
  inheritAttrs: false,
});
const props = defineProps({
  closeHandlerOverride: Function,
});
const isVisible = defineModel({ type: Boolean });

// 'escape' to close
Mousetrap.bind("esc", () => {
  if (isVisible.value) {
    closeHandler();
  }
});

function closeHandler() {
  if (props.closeHandlerOverride) {
    props.closeHandlerOverride();
  } else {
    isVisible.value = false;
  }
}
</script>
