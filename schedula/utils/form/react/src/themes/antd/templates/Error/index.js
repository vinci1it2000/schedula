import {Modal} from 'antd';

const error = ({content, ...props}) => {
    Modal.error({content, ...props});
};
export default error;