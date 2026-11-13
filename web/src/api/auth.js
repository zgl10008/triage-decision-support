import request from '../utils/request';

const authApi = {
  login: (payload) => {
    return request.post('/api/auth/login', payload);
  },

  logout: () => {
    return request.post('/api/auth/logout');
  },

  me: () => {
    return request.get('/api/auth/me');
  }
};

export default authApi;
