import {Button, Result} from 'antd';
import {Link} from "react-router-dom";
import React from "react";

const NotFound = ({children, homePath = '/', ...props}) => {
    return <Result
        status="404"
        title="404"
        subTitle="Sorry, the page you visited does not exist."
        extra={<Link to={homePath}>
            <Button type="primary">
                {children || 'Back Home'}
            </Button>
        </Link>}
        {...props}
    />

};
export default NotFound;