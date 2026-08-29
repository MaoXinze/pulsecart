import { defHttp } from '/@/utils/http/axios';
import { getMenuListResultModel } from './model/menuModel';
import { useUserStoreWithOut } from '@/store/modules/user';
import { setAuthCache } from '@/utils/auth';
import { TOKEN_KEY } from '@/enums/cacheEnum';

enum Api {
  GetMenuList = '/sys/permission/getUserPermissionByToken',
  // 【QQYUN-8487】
  // SwitchVue3Menu = '/sys/switchVue3Menu',
}

/**
 * @description: Get user menu based on id
 */

export const getMenuList = () => {
  return new Promise((resolve) => {
    //为了兼容mock和接口数据
    defHttp.get<getMenuListResultModel>({ url: Api.GetMenuList }).then((res) => {
      if (Array.isArray(res)) {
        resolve(res);
      } else {
        resolve(res['menu']);
      }
    });
  });
};

/**
 * @description: 获取后台菜单权限和按钮权限
 */
export async function getBackMenuAndPerms() {
  try {
    return await defHttp.get({ url: Api.GetMenuList, timeout: 120 * 1000 });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error || '');
    console.log('接口 getBackMenuAndPerms 异常错误信息：', error);
    // Token过期失效，直接跳转登录页面 2025-09-08 scott
    if (message.includes('timeout') || message.includes('401') || message.includes('500')) {
      const userStore = useUserStoreWithOut();
      userStore.setToken('');
      setAuthCache(TOKEN_KEY, null);
      return undefined;
    }
    throw error;
  }
}

/**
 * 切换成vue3菜单
 */
// export const switchVue3Menu = () => {
//   return new Promise((resolve) => {
//     defHttp.get({ url: Api.SwitchVue3Menu });
//   });
// };
