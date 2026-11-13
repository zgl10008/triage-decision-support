package org.checkclassification.mapper;

 // UserAccountMapper

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.checkclassification.pojo.entity.UserAccount;

@Mapper
public interface UserAccountMapper extends BaseMapper<UserAccount> {
}
