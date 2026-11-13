package org.checkclassification.service.impl;

 // SysPermissionServiceImpl

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.checkclassification.mapper.SysPermissionMapper;
import org.checkclassification.pojo.entity.SysPermission;
import org.checkclassification.service.SysPermissionService;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class SysPermissionServiceImpl extends ServiceImpl<SysPermissionMapper, SysPermission> implements SysPermissionService {
    @Override
    public List<String> findPermCodesByUserId(Long userId) {
        return baseMapper.findPermCodesByUserId(userId);
    }
}
