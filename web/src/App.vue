<template>
  <router-view v-if="route.meta.public" />
  <AppLayout v-else />
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";
import AppLayout from "@/layouts/AppLayout.vue";

const route = useRoute();
</script>
