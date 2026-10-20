<template>
  <div
    v-if="
      images.length > 0 &&
      ($route.path.startsWith('/new') || $route.path.startsWith('/edit'))
    "
    ref="el"
    class="grid gap-2"
    :style="gridStyle"
  >
    <div
      v-for="img in images"
      :key="img"
      class="relative"
      :class="
        images.length === 1
          ? 'full-cover-image-single'
          : 'full-cover-image-mult'
      "
    >
      <img :src="img" class="cursor-move rounded" />
      <div
        class="absolute top-0 right-0 px-1 bg-white dark:bg-gray-900 m-2 rounded hover:text-red-500 cursor-pointer"
        @click="removeImage(img)"
      >
        <UIcon name="i-carbon-trash-can" />
      </div>
    </div>
  </div>

  <template v-else-if="props.imgConfigs && props.imgConfigs.length">
    <MyFancyBox :style="gridStyle">
      <!-- 视频：原生 video 标签，浏览器会显示封面帧 -->
      <div
        v-for="(imgConfig, z) in videoConfigs"
        :key="'v' + z"
        class="video-cell"
        :class="
          images.length === 1
            ? 'full-cover-image-single'
            : 'full-cover-image-mult'
        "
      >
        <video
          class="rounded cursor-pointer"
          :src="imgConfig.url"
          :poster="imgConfig.thumbUrl"
          preload="metadata"
          controls
          playsinline
        ></video>
      </div>
      <!-- 图片 -->
      <div
        v-for="(imgConfig, z) in imageConfigs"
        :key="'i' + z"
        :href="imgConfig.url"
        :class="
          images.length === 1
            ? 'full-cover-image-single'
            : 'full-cover-image-mult'
        "
      >
        <img
          class="cursor-zoom-in rounded"
          :src="imgConfig.thumbUrl"
          :onerror="`javascript:this.src='${imgConfig.url}';this.onerror=null`"
        />
      </div>
    </MyFancyBox>
  </template>
</template>

<script setup lang="ts">
import type { SysConfigVO } from "~/types";

interface ImgConfig {
  url: string;
  thumbUrl: string;
}

const VIDEO_EXT = [".mp4", ".mov", ".m4v", ".webm", ".mkv"];

const isVideo = (url: string) => {
  const clean = (url || "").split("?")[0].toLowerCase();
  return VIDEO_EXT.some((ext) => clean.endsWith(ext));
};

const sysConfig = useState<SysConfigVO>("sysConfig");
const route = useRoute();
const el = ref(null);
const props = defineProps<{ imgs?: string; imgConfigs?: ImgConfig[] }>();
const emit = defineEmits(["removeImage", "dragImage"]);
const images = ref<string[]>((props.imgs || "").split(",").filter(Boolean));

// 视频和图片分开渲染 —— 视频用<video>，图片继续走 Fancybox 灯箱
const videoConfigs = computed<ImgConfig[]>(() =>
  (props.imgConfigs || []).filter((c) => isVideo(c.url))
);
const imageConfigs = computed<ImgConfig[]>(() =>
  (props.imgConfigs || []).filter((c) => !isVideo(c.url))
);

watch(props, () => {
  images.value = (props.imgs || "").split(",").filter(Boolean);
});

watch(images, () => {
  emit("dragImage", images.value);
});

const removeImage = async (img: string) => {
  await useMyFetch("/memo/removeImage", {
    img,
  });
  emit("removeImage", img);
};

onMounted(() => {
  if (route.path.startsWith("/new") || route.path.startsWith("/edit")) {
    setTimeout(() => {
      void import("@vueuse/integrations/useSortable").then(({ useSortable }) => {
        useSortable(el, images);
      });
    }, 500);
  }
});

const gridStyle = computed(() => {
  let style = "max-width:100%; display:grid; gap: 0.5rem; align-items: start;"; // 确保内容顶部对齐
  switch (images.value.length) {
    case 1:
      style += "grid-template-columns: 1fr; max-width:60%;";
      break;
    case 2:
      style += "grid-template-columns: 1fr 1fr; aspect-ratio: 2 / 1;";
      break;
    case 3:
      style += "grid-template-columns: 1fr 1fr 1fr; aspect-ratio: 3 / 1;";
      break;
    case 4:
      style += "grid-template-columns: 1fr 1fr; aspect-ratio: 1;";
      break;
    default:
      style += "grid-template-columns: 1fr 1fr 1fr;";
  }
  return style;
});
</script>

<style scoped>
.video-cell {
  width: 100%;

  > video {
    width: 100%;
    max-height: 300px;
    object-fit: contain;
    background: #000;
    display: block;
  }
}

.full-cover-image-mult {
  width: 100%;
  max-height: 300px;
  aspect-ratio: 1 / 1;

  > img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
  }
}

.full-cover-image-single {
  width: fit-content;

  > img {
    max-height: 300px;
    object-fit: cover;
    object-position: center;
  }
}
</style>
