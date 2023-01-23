import {Button} from 'antd';


const Submit = ({children, render, ...props}) => (
    <Button htmlType="submit" formMethod="POST" type="primary" {...props}>
        {children || "submit"}
    </Button>);

export default Submit;
