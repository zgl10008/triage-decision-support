package org.checkclassification.config;

 // CharArrayVarcharTypeHandler

import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;

import java.sql.CallableStatement;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

public class CharArrayVarcharTypeHandler extends BaseTypeHandler<char[]> {

    @Override
    public void setNonNullParameter(PreparedStatement ps, int i, char[] parameter, JdbcType jdbcType) throws SQLException {
        ps.setString(i, new String(parameter));
    }

    @Override
    public char[] getNullableResult(ResultSet rs, String columnName) throws SQLException {
        return toCharArray(rs.getString(columnName));
    }

    @Override
    public char[] getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
        return toCharArray(rs.getString(columnIndex));
    }

    @Override
    public char[] getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
        return toCharArray(cs.getString(columnIndex));
    }

    private char[] toCharArray(String value) {
        return value == null ? null : value.toCharArray();
    }
}
