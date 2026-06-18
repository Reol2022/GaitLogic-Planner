<template>
  <router-view v-if="route.meta.public" />
  <AppLayout v-else />
  <AuthDialog />
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";
import AppLayout from "@/layouts/AppLayout.vue";
import AuthDialog from "@/components/AuthDialog.vue";

const route = useRoute();
</script>
