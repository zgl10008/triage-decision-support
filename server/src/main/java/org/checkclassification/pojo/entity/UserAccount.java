package org.checkclassification.pojo.entity;

 // UserAccount

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import org.checkclassification.config.CharArrayVarcharTypeHandler;

import java.time.LocalDateTime;
import java.util.Arrays;

@Data
@TableName(value = "user_account", autoResultMap = true)
public class UserAccount {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("username")
    private String username;

    @TableField(value = "password", typeHandler = CharArrayVarcharTypeHandler.class)
    private char[] password;

    @TableField(value = "create_time", fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(value = "update_time", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public void clearPassword() {
        if (password != null) {
            Arrays.fill(password, '\0');
            password = null;
        }
    }
}
