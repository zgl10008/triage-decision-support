package org.checkclassification.mapper;

 // SysPermissionMapper

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.checkclassification.pojo.entity.SysPermission;

import java.util.List;

@Mapper
public interface SysPermissionMapper extends BaseMapper<SysPermission> {

    @Select("SELECT p.perm_code FROM sys_permission p JOIN sys_role_permission rp ON p.id=rp.permission_id JOIN sys_user_role ur ON ur.role_id=rp.role_id WHERE ur.user_id=#{userId}")
    List<String> findPermCodesByUserId(Long userId);
}
