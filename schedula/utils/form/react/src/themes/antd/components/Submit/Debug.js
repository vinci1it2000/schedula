import {Button} from 'antd';


const SubmitDebug = ({children, render, ...props}) => (
    <Button
        htmlType="submit"
        formMethod="POST"
        type="primary"
        headers={JSON.stringify({'Debug': 'true'})} {...props}>
        {children || "debug"}
    </Button>);

export default SubmitDebug;
