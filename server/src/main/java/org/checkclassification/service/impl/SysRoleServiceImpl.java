package org.checkclassification.service.impl;

 // SysRoleServiceImpl

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.checkclassification.mapper.SysRoleMapper;
import org.checkclassification.pojo.entity.SysRole;
import org.checkclassification.service.SysRoleService;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class SysRoleServiceImpl extends ServiceImpl<SysRoleMapper, SysRole> implements SysRoleService {
    @Override
    public List<String> findRoleCodesByUserId(Long userId) {
        return baseMapper.findRoleCodesByUserId(userId);
    }
}
