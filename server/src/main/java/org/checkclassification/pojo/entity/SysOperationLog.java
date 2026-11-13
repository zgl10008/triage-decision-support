package org.checkclassification.pojo.entity;

 // SysOperationLog

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("sys_operation_log")
public class SysOperationLog {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String username;
    private String requestMethod;
    private String requestPath;
    private String clientIp;
    private Integer statusCode;
    private String message;
    private LocalDateTime createTime;

}
