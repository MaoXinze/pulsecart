import type { AppRouteModule } from '/@/router/types';
import { LAYOUT } from '/@/router/constant';

const pulsecart: AppRouteModule = {
  path: '/pulsecart',
  name: 'PulseCart',
  component: LAYOUT,
  redirect: '/pulsecart/operations',
  meta: {
    title: 'PulseCart 商品体验',
    icon: 'ant-design:shopping-outlined',
    orderNo: 15,
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
};

export default pulsecart;
