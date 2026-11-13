package org.checkclassification.pojo.entity;

 // SysPermission

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("sys_permission")
public class SysPermission {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String permName;
    private String permCode;
    private String path;
    private String method;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}

