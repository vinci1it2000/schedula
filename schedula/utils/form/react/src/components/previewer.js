import React, {useState, Suspense} from "react";

const Box = React.lazy(() => import('@mui/material/Box'));

export default function FilePreviewer({file, ...props}) {
    const [imagePreview, setImagePreview] = useState(null);
    const [videoPreview, setVideoPreview] = useState(null);
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = (readerEvent) => {
        if (file.type.includes("image")) {
            setImagePreview(readerEvent.target.result);
        } else if (file.type.includes("video")) {
            setVideoPreview(readerEvent.target.result);
        }
    }
    return <Suspense>
        <Box {...props}>
            {imagePreview != null &&
                <img style={{minHeight: '20px', maxHeight: '80px'}}
                     src={imagePreview} alt=""/>}
            {videoPreview != null &&
                <video style={{minHeight: '20px', maxHeight: '80px'}}
                       controls
                       src={videoPreview}></video>}
        </Box>
    </Suspense>

}