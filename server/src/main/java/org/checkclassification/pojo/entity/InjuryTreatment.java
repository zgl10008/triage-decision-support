package org.checkclassification.pojo.entity;

 // InjuryTreatment

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("injury_treatment")
public class InjuryTreatment {
    // 主键ID
    @TableId(type = IdType.AUTO)
    private Integer id;

    private String injuryType;

    private String classification;

    private String description;

    // 创建时间（自动填充）
    private LocalDateTime createTime;

    // 更新时间（自动填充）
    private LocalDateTime updateTime;
}
