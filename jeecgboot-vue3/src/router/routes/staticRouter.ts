import type { AppRouteRecordRaw } from '/@/router/types';
import { LAYOUT } from '/@/router/constant';

// 产品主入口不依赖历史 sys_permission 数据，保证旧演示库升级后可直接访问。
export const staticRoutesList: AppRouteRecordRaw[] = [
  {
    path: '/pulsecart',
    name: 'PulseCart',
    component: LAYOUT,
    redirect: '/pulsecart/operations',
    meta: {
      title: 'PulseCart 商品体验',
      icon: 'ant-design:shopping-outlined',
      orderNo: 1,
    },
    children: [
      {
        path: 'operations',
        name: 'PulseCartOperations',
        component: () => import('/@/views/sentiment/operations/index.vue'),
        meta: {
          title: '体验问题闭环',
          icon: 'ant-design:deployment-unit-outlined',
        },
      },
    ],
  },
];
