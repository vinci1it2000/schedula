import {
    DraggableModalProvider
} from 'ant-design-draggable-modal/packages/ant-design-draggable-modal'
import 'ant-design-draggable-modal/packages/ant-design-draggable-modal/index.css'


const ModalProvider = ({children, ...props}) => {
    return (
        <DraggableModalProvider {...props}>
            {children}
        </DraggableModalProvider>
    );
};
export default ModalProvider;