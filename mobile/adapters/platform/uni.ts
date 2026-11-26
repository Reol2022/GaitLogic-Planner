export const platform = {
  navigate(url: string) { uni.navigateTo({ url }); },
  tab(url: string) { uni.switchTab({ url }); },
  relaunch(url: string) { uni.reLaunch({ url }); },
  copy(data: string) { uni.setClipboardData({ data }); },
};
